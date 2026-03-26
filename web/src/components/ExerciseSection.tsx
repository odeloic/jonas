import type { AssignmentSection } from "../api/types";
import ExerciseItem from "./ExerciseItem";

interface ExerciseSectionProps {
  section: AssignmentSection;
}

export default function ExerciseSection({ section }: ExerciseSectionProps) {
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
        />
      ))}
    </section>
  );
}
