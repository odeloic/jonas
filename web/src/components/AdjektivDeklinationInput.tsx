import type { AdjektivDeklinationExerciseItem } from "../api/types";

interface Props {
  item: AdjektivDeklinationExerciseItem;
  index: number;
  value: string[];
  onChange: (value: string[]) => void;
  disabled: boolean;
}

export default function AdjektivDeklinationInput({
  item,
  index,
  value,
  onChange,
  disabled,
}: Props) {
  const selected = value[0] ?? "";
  const [before, after] = splitOnBlank(item.question);

  return (
    <div className="space-y-3">
      <p className="text-gray-900">
        <span className="text-gray-400 text-sm mr-2">{index}.</span>
        {before}
        <span className="inline-block min-w-12 border-b-2 border-dotted border-gray-400 mx-1 text-center text-gray-900">
          {selected || " "}
        </span>
        {after}
      </p>
      <div className="flex flex-wrap gap-1.5">
        {item.candidate_endings.map((ending) => (
          <button
            key={ending}
            type="button"
            disabled={disabled}
            onClick={() => onChange([ending])}
            className={`px-3 py-1.5 border rounded text-sm transition-colors disabled:opacity-50 ${
              selected === ending
                ? "border-gray-900 bg-gray-900 text-white"
                : "border-gray-300 text-gray-700 hover:bg-gray-50"
            }`}
          >
            {ending}
          </button>
        ))}
      </div>
    </div>
  );
}

function splitOnBlank(question: string): [string, string] {
  const idx = question.indexOf("___");
  if (idx < 0) return [question, ""];
  return [question.slice(0, idx), question.slice(idx + 3)];
}
